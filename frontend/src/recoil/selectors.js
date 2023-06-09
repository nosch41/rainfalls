import { selector, selectorFamily } from "recoil";
import { filtersAtom } from "./atoms";
import _ from "../util";
import dayjs from "dayjs";
import { DefaultApi as Api } from "../client";

export const filtersToQueryParamsState = selector({
  key: "filtersToQueryParamsState",
  get: ({ get }) => {
    const filters = get(filtersAtom);
    const paramsObj = Object.keys(filters).reduce((obj, field) => {
      filters[field].conditions
        .filter((condition) => condition.enabled)
        .forEach((condition) => {
          obj[field + "__" + condition.operator] =
            field === _.START_TIME
              ? dayjs(condition.value).format()
              : condition.value;
        });
      return obj;
    }, {});

    return new URLSearchParams(paramsObj).toString();
  },
});

export const filteredEventsState = selectorFamily({
  key: "filteredEvents",
  get:
    ({ filterParams }) =>
    async () =>
      (
        await Api.queryQueryGet({
          filterParams: filterParams,
          fields: [
            "event_id",
            "area",
            "severity_index",
            "start_time",
            "length",
            "meanLat",
            "meanLon",
            "meanPrec",
            "maxPrec",
          ],
        }).catch((err) => console.log(err))
      ).results,
});
